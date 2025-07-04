"""A collection of tools used by several classes"""
from modules.exceptions import HostgroupError

def convert_recordset(recordset):
    """Converts netbox RedcordSet to list of dicts."""
    recordlist = []
    for record in recordset:
        recordlist.append(record.__dict__)
    return recordlist


def build_path(endpoint, list_of_dicts):
    """
    Builds a path list of related parent/child items.
    This can be used to generate a joinable list to
    be used in hostgroups.
    """
    item_path = []
    itemlist = [i for i in list_of_dicts if i["name"] == endpoint]
    item = itemlist[0] if len(itemlist) == 1 else None
    item_path.append(item["name"])
    while item["_depth"] > 0:
        itemlist = [i for i in list_of_dicts if i["name"] == str(item["parent"])]
        item = itemlist[0] if len(itemlist) == 1 else None
        item_path.append(item["name"])
    item_path.reverse()
    return item_path


def proxy_prepper(proxy_list, proxy_group_list):
    """
    Function that takes 2 lists and converts them using a
    standardized format for further processing.
    """
    output = []
    for proxy in proxy_list:
        proxy["type"] = "proxy"
        proxy["id"] = proxy["proxyid"]
        proxy["idtype"] = "proxyid"
        proxy["monitored_by"] = 1
        output.append(proxy)
    for group in proxy_group_list:
        group["type"] = "proxy_group"
        group["id"] = group["proxy_groupid"]
        group["idtype"] = "proxy_groupid"
        group["monitored_by"] = 2
        output.append(group)
    return output


def field_mapper(host, mapper, nbdevice, logger):
    """
    Maps NetBox field data to Zabbix properties.
    Used for Inventory, Usermacros and Tag mappings.
    """
    data = {}
    # Let's build an dict for each property in the map
    for nb_field, zbx_field in mapper.items():
        field_list = nb_field.split("/")  # convert str to list based on delimiter
        # start at the base of the dict...
        value = nbdevice
        # ... and step through the dict till we find the needed value
        for item in field_list:
            value = value[item] if value else None
        # Check if the result is usable and expected
        # We want to apply any int or float 0 values,
        # even if python thinks those are empty.
        if (value and isinstance(value, int | float | str)) or (
            isinstance(value, int | float) and int(value) == 0
        ):
            data[zbx_field] = str(value)
        elif not value:
            # empty value should just be an empty string for API compatibility
            logger.debug(
                f"Host {host}: NetBox lookup for "
                f"'{nb_field}' returned an empty value"
            )
            data[zbx_field] = ""
        else:
            # Value is not a string or numeral, probably not what the user expected.
            logger.error(
                f"Host {host}: Lookup for '{nb_field}'"
                " returned an unexpected type: it will be skipped."
            )
    logger.debug(
        f"Host {host}: Field mapping complete. "
        f"Mapped {len(list(filter(None, data.values())))} field(s)"
    )
    return data


def remove_duplicates(input_list, sortkey=None):
    """
    Removes duplicate entries from a list and sorts the list
    """
    output_list = []
    if isinstance(input_list, list):
        output_list = [dict(t) for t in {tuple(d.items()) for d in input_list}]
    if sortkey and isinstance(sortkey, str):
        output_list.sort(key=lambda x: x[sortkey])
    return output_list


def verify_hg_format(hg_format, device_cfs=None, vm_cfs=None, hg_type="dev", logger=None):
    """
    Verifies hostgroup field format
    """
    if not device_cfs:
        device_cfs = []
    if not vm_cfs:
        vm_cfs = []
    allowed_objects = {"dev": ["location",
                              "rack",
                              "role",
                              "manufacturer",
                              "region",
                              "site",
                              "site_group",
                              "tenant",
                              "tenant_group",
                              "platform",
                              "cluster"]
                      ,"vm": ["cluster_type",
                              "role",
                              "manufacturer",
                              "region",
                              "site",
                              "site_group",
                              "tenant",
                              "tenant_group",
                              "cluster",
                              "device",
                              "platform"]
                       ,"cfs": {"dev": [], "vm": []}
                      }
    for cf in device_cfs:
        allowed_objects['cfs']['dev'].append(cf.name)
    for cf in vm_cfs:
        allowed_objects['cfs']['vm'].append(cf.name)
    hg_objects = []
    if isinstance(hg_format,list):
        for f in hg_format:
            hg_objects = hg_objects + f.split("/")
    else:
        hg_objects = hg_format.split("/")
    hg_objects = sorted(set(hg_objects))
    for hg_object in hg_objects:
        if (hg_object not in allowed_objects[hg_type] and
            hg_object not in allowed_objects['cfs'][hg_type]):
            e = (
                f"Hostgroup item {hg_object} is not valid. Make sure you"
                " use valid items and separate them with '/'."
            )
            logger.error(e)
            raise HostgroupError(e)


def sanatize_log_output(data):
    """
    Used for the update function to Zabbix which
    shows the data that its using to update the host.
    Removes and sensitive data from the input.
    """
    if not isinstance(data, dict):
        return data
    sanitized_data = data.copy()
    # Check if there are any sensitive macros defined in the data
    if "macros" in data:
        for macro in sanitized_data["macros"]:
            # Check if macro is secret type
            if not macro["type"] == str(1):
                continue
            macro["value"] = "********"
    # Check for interface data
    if "interfaceid" in data:
        # Interface ID is a value which is most likely not helpful
        # in logging output or for troubleshooting.
        del sanitized_data["interfaceid"]
        # InterfaceID also hints that this is a interface update.
        # A check is required if there are no macro's used for SNMP security parameters.
        if not "details" in data:
            return sanitized_data
        for key, detail in sanitized_data["details"].items():
            # If the detail is a secret, we don't want to log it.
            if key in ("authpassphrase", "privpassphrase", "securityname", "community"):
                # Check if a macro is used.
                # If so then logging the output is not a security issue.
                if detail.startswith("{$") and detail.endswith("}"):
                    continue
                # A macro is not used, so we sanitize the value.
                sanitized_data["details"][key] = "********"
    return sanitized_data
