requets_url = "https://mtec.by/wp-admin/admin-ajax.php"
ejournal_login_url = "http://office.mtec.by/"
ejournal_profile_url = "http://office.mtec.by/profile.php"
ejournal_profile_period_url = "http://office.mtec.by/profile.php?period="

base_request_headers = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
}

ejournal_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
}

request_data = {
    "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "action": "getSearchParameters",
    "rtype": "stds",
}
