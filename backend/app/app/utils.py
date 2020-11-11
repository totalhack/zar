def extract_header_params(headers):
    host = headers.get("x-forwarded-host", None) or headers.get("host", None)
    ip = (
        headers.get("x-forwarded-for", None)
        or headers.get("x-real-ip", None)
        or headers.get("forwarded", None)
    )
    user_agent = headers.get("user-agent", None)
    referer = headers.get("referer", None)
    return dict(host=host, ip=ip, user_agent=user_agent, referer=referer)
