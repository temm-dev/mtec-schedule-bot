"""
MTEC Schedule Bot - Main Entry Point

This module contains the main entry point for the Telegram bot application.
It handles initialization, startup, and graceful shutdown of all components.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import aiofiles
import coloredlogs
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config.bot_config import TOKEN
from config.paths import WORKSPACE
from core.dependencies import container
from services.database import db_manager
from services.schedule_checker_service import ScheduleChecker
from services.schedule_service import ScheduleService
from utils.markup import _ensure_initialized

# Configure structured logging
coloredlogs.install(
    level=logging.INFO,
    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class BotApplication:
    """Main application class for the Telegram bot."""
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dispatcher: Optional[Dispatcher] = None
        self.schedule_checker: Optional[ScheduleChecker] = None
        self.schedule_checker_task: Optional[asyncio.Task] = None
        self.is_shutting_down: bool = False
        
    async def initialize_workspace(self) -> tuple[Path, Path, Path]:
        """Initialize workspace directories and required files."""
        try:
            workspace_dir = Path(WORKSPACE)
            workspace_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Workspace initialized: {workspace_dir}")

            blacklist_path = workspace_dir / "blacklist.txt"
            blacklist_path.touch(exist_ok=True)
            
            current_date_path = workspace_dir / "current_date.txt"
            
            return workspace_dir, blacklist_path, current_date_path
            
        except Exception as e:
            logger.error(f"Failed to initialize workspace: {e}")
            raise

    async def setup_bot(self) -> None:
        """Initialize bot instance and configure webhook settings."""
        try:
            self.bot = Bot(token=TOKEN)
            await self.bot.delete_webhook(drop_pending_updates=True)
            container._bot = self.bot
            logger.info("Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise

    async def setup_database(self) -> None:
        """Initialize database connection and tables."""
        try:
            container._db_manager = db_manager
            await db_manager.init_db()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def setup_schedule_checker(self) -> None:
        """Initialize and start the schedule checker service."""
        try:
            self.schedule_checker = ScheduleChecker(self.bot, self.db_manager)
            self.schedule_checker_task = asyncio.create_task(
                self.schedule_checker.run_schedule_check()
            )
            logger.info("Schedule checker started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start schedule checker: {e}")
            raise

    async def setup_handlers(self) -> None:
        """Initialize and configure message handlers."""
        try:
            self.dispatcher = Dispatcher(storage=MemoryStorage())
            
            from core.handlers import setup_handlers
            setup_handlers(self.dispatcher)
            
            logger.info("Handlers configured successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup handlers: {e}")
            raise

    async def initialize_current_dates(self, current_date_path: Path) -> None:
        """Fetch and store current schedule dates from the server."""
        try:
            schedule_service = ScheduleService()
            dates = await schedule_service.get_dates_schedule()
            
            async with aiofiles.open(current_date_path, "w", encoding="utf-8") as file:
                await file.write("\n".join(dates))
                
            logger.info(f"Current dates saved: {len(dates)} dates")
            
        except Exception as e:
            logger.error(f"Failed to initialize current dates: {e}")
            raise

    async def start(self) -> None:
        """Start the bot application with all components."""
        try:
            logger.info("Starting MTEC Schedule Bot...")
            
            # Initialize workspace
            _, _, current_date_path = await self.initialize_workspace()
            
            # Initialize markup utilities
            await _ensure_initialized()
            
            # Initialize current dates
            await self.initialize_current_dates(current_date_path)
            
            # Setup bot
            await self.setup_bot()
            
            # Setup database
            await self.setup_database()
            
            # Setup schedule checker
            await self.setup_schedule_checker()
            
            # Setup handlers
            await self.setup_handlers()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.cleanup()
            raise

    async def run(self) -> None:
        """Run the bot with polling."""
        try:
            logger.info("Starting bot polling...")
            await self.dispatcher.start_polling(self.bot)
            
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise

    async def cleanup(self) -> None:
        """Perform graceful shutdown and cleanup."""
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        logger.info("Starting graceful shutdown...")
        
        try:
            # Cancel schedule checker
            if self.schedule_checker_task and not self.schedule_checker_task.done():
                self.schedule_checker_task.cancel()
                try:
                    await self.schedule_checker_task
                except asyncio.CancelledError:
                    logger.info("Schedule checker cancelled")
                except Exception as e:
                    logger.warning(f"Error cancelling schedule checker: {e}")

            # Close bot session
            if self.bot:
                await self.bot.session.close()
                logger.info("Bot session closed")

            # Close database connection
            if hasattr(db_manager, 'close'):
                await db_manager.close()
                logger.info("Database connection closed")
                
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    @property
    def db_manager(self):
        """Get database manager from container."""
        return container._db_manager


app = BotApplication()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(app.cleanup())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point."""
    setup_signal_handlers()
    
    try:
        await app.start()
        await app.run()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
        
    finally:
        await app.cleanup()
        
    return 0


def run_with_error_handling():
    """Run the application with comprehensive error handling."""
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_with_error_handling()
