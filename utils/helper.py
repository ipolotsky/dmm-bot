import re


def safe_list_get(list_object, idx, default=""):
    try:
        return list_object[idx]
    except KeyError:
        return default


def get_vk(text):
    pattern_link = re.compile(r'(https://|http://|)(www\.|)vk\.com/([A-Za-z\d\-\_\.]+)', flags=re.IGNORECASE)
    pattern_username = re.compile(r'(@|)([A-Za-z0-9\-\_\.]+)')

    if re.search("^http", text) or re.search("^vk\.com", text, re.IGNORECASE):
        try:
            return "https://vk.com/" + pattern_link.search(text).group(3)
        except AttributeError:
            return False
    else:
        try:
            return "https://vk.com/" + pattern_username.search(text).group(2)
        except AttributeError:
            return False
