def format_error_message(function_name: str, error: Exception) -> str:
    frame_length = len(function_name)

    top_bottom_frame = "!" + "-" * (frame_length + (2 * len("                 "))) + "!"
    middle_frame = f"                | {function_name} |                "

    result = f"\n{top_bottom_frame}\n{middle_frame}\n{error}\n{top_bottom_frame}\n"
    return result
