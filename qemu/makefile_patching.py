
def patch_makefile(mf_full_name, obj_base_name, obj_var_name, config_flag):
    """ The function ensures that object file with name obj_base_name is
registered in Makefile with name mf_full_name using variable with name
obj_var_name. """
    mf = open(mf_full_name, "r")

    try:
        lines = mf.readlines()
    except BaseException as e:
        mf.close()
        raise e

    mf.close()

    obj_var_token = obj_var_name + "-" + config_flag

    for line in lines:
        tokens = set([ s.strip() for s in line.split(" ") ])
        if not obj_var_token in tokens:
            continue
        if obj_base_name in tokens:
            break
    else:
        if lines:
            nl_at_eof = (lines[-1][-1] == "\n")
        else:
            nl_at_eof = True

        mf = open(mf_full_name, "a")
        try:
            # Register object file with name obj_base_name
            mf.write(
                  ("" if nl_at_eof else "\n")
                + obj_var_token
                + " += "
                + obj_base_name
                + ("\n" if nl_at_eof else "")
            )
        except BaseException as e:
            mf.close()
            raise e

        mf.close()

    # Object file with name obj_base_name is already registered.
