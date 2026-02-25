"""HTTP request configuration module for MTEC schedule bot.

This module contains URLs, headers, and data for all HTTP requests to external APIs.
Includes settings for fetching schedule data from the college website and accessing
the electronic journal system.
"""

from typing import Dict, Final

# API endpoints
REQUESTS_URL: Final[str] = "https://mtec.by/wp-admin/admin-ajax.php"
EJOURNAL_LOGIN_URL: Final[str] = "http://office.mtec.by/"
EJOURNAL_PROFILE_URL: Final[str] = "http://office.mtec.by/profile.php"
EJOURNAL_PROFILE_PERIOD_URL: Final[str] = "http://office.mtec.by/profile.php?period="

# HTTP headers for schedule requests
BASE_REQUEST_HEADERS: Final[Dict[str, str]] = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-origin",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Mode": "cors",
    "Host": "mtec.by",
    "Origin": "https://mtec.by",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Referer": "https://mtec.by/ru/students/schedule",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "X-Requested-With": "XMLHttpRequest",
}

# HTTP headers for e-journal requests
EJOURNAL_HEADERS: Final[Dict[str, str]] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Host": "office.mtec.by",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# Request data for student schedule
REQUEST_DATA: Final[Dict[str, str]] = {
    "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "action": "getSearchParameters",
    "rtype": "stds",
}

# Request data for mentor schedule
REQUEST_DATA_MENTORS: Final[Dict[str, str]] = {
    "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "action": "getSearchParameters",
    "rtype": "prep",
}

# Request actions
ACTION_GET_SEARCH_PARAMETERS: Final[str] = "getSearchParameters"
REQUEST_TYPE_STUDENTS: Final[str] = "stds"
REQUEST_TYPE_MENTORS: Final[str] = "prep"
