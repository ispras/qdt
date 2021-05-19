__all__ = [
    "patch_makefile"
]

def patch_makefile(mf_full_name, obj_base_name, obj_var_name, config_flag):
    """ The function ensures that object file with name obj_base_name is
registered in Makefile with name mf_full_name using variable with name
obj_var_name. """

    with open(mf_full_name, "r") as mf:
        lines = mf.readlines()

    normal_obj_var_token = obj_var_name + "-" + config_flag
    ifeq_obj_var_token = obj_var_name + "-y"
    obj_var_token = normal_obj_var_token

    ifeq_cond_directive = "ifeq (" + config_flag + ", y)\n"

    patch_line_n = None
    ifeq_patch_line_n = None

    in_ifeq = False

    for n, line in enumerate(lines):
        if line == ifeq_cond_directive:
            in_ifeq = True
            obj_var_token = ifeq_obj_var_token
            continue

        if line == "endif\n":
            in_ifeq = False
            obj_var_token = normal_obj_var_token
            continue

        tokens = set([ s.strip() for s in line.split(" ") ])

        # Patch the makefile just below last obj_base_name usage.
        for t in tokens:
            if t.startswith(obj_var_name):
                if in_ifeq:
                    ifeq_patch_line_n = n + 1
                else:
                    patch_line_n = n + 1
                break

        if obj_var_token not in tokens:
            continue
        if obj_base_name in tokens:
            break
    else:
        # Register object file with name obj_base_name.
        if ifeq_patch_line_n:
            # Prefer to register object file inside `ifeq` statement.
            patch_line = (
                ifeq_obj_var_token
                + " += "
                + obj_base_name
            )
            lines.insert(ifeq_patch_line_n, patch_line + "\n")
        else:
            patch_line = (
                obj_var_token
                + " += "
                + obj_base_name
            )

            if patch_line_n is None or patch_line_n == len(lines):
                # Add NL at EOF if file is empty or current last line have NL.
                if not lines or lines[-1][-1] == "\n":
                    patch_line += "\n"

                lines.append(patch_line)
            else:
                lines.insert(patch_line_n, patch_line + "\n")

        with open(mf_full_name, "w") as mf:
            mf.write("".join(lines))

    # Object file with name obj_base_name is already registered.
