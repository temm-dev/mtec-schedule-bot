requets_url = "https://mtec.by/wp-admin/admin-ajax.php"
ejournal_login_url = "http://office.mtec.by/"
ejournal_profile_url = "http://office.mtec.by/profile.php"
ejournal_profile_period_url = "http://office.mtec.by/profile.php?period="

base_request_headers = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-origin",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Mode": "cors",
    "Host": "mtec.by",
    "Origin": "https://mtec.by",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Referer": "https://mtec.by/ru/students/schedule",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "X-Requested-With": "XMLHttpRequest",
}


ejournal_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Host": "office.mtec.by",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


request_data = {
    "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "action": "getSearchParameters",
    "rtype": "stds",
}
