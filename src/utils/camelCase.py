def camelCase(obj: dict) -> dict:
    """Function to camel case a snake cased dict

    Args:
        obj (dict): Dict to be camel cased

    Returns:
        dict: Camel Cased dict
    """
    camelCased = {}
    for key, value in obj.items():
        temp = key.split('_')
        res = temp[0] + ''.join(ele.title() for ele in temp[1:])
        camelCased[res] = value

    return camelCased
