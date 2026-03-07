from robot.browser import has_local_storage


def is_cookie_present():
    return has_local_storage("my.cynteract.com")
