from argparse import ArgumentParser

def get_msgstr(po_record):
    riter = iter(po_record)
    msgstr_code = ""
    for rl in riter:
        if rl.startswith("msgstr"):
            tmp = rl[6:-1]
            if tmp != '""':
                msgstr_code += tmp
            break

    for rl in riter:
        tmp = rl[:-1]
        if tmp != '""':
            msgstr_code += tmp

    msgstr = eval(msgstr_code)
    return msgstr

if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("po", nargs = 2)

    args = ap.parse_args()

    pos = args.po
    # print(pos)

    for i in range(0, 2):
        f = open(pos[i], "rb")
        po_lines = list(f.readlines())
        locals()["po" + str(i) + "_lines"] = po_lines
        f.close()

        # parse *.po
        if po_lines[-1] == "\n":
            liter = iter(po_lines)
        else:
            liter = iter(po_lines + ["\n"])

        # skip first block
        while next(liter) != "\n":
            pass

        po_content = {}
        po_record = []

        for l in liter:
            if l != "\n":
                po_record.append(l)
                continue

            if not po_record:
                continue

            riter = iter(po_record)
            msgid_code = ""
            for rl in riter:
                if rl.startswith("msgid"):
                    tmp = rl[6:-1]
                    if tmp != '""':
                        msgid_code += tmp
                    break

            for rl in riter:
                if rl.startswith("msgstr"):
                    break
                tmp = rl[:-1]
                if tmp != '""':
                    msgid_code += tmp

            msgid = eval(msgid_code)

            po_content[msgid] = po_record

            po_record = []

        locals()["po" + str(i) + "_content"] = po_content

    print("lines: " + str(len(po0_lines)) + "/" + str(len(po1_lines)))
    print("records: " + str(len(po0_content)) + "/" + str(len(po1_content)))

    both = set()
    both |= set(po0_content) | set(po1_content)

    for key in po0_content:
        if key not in po1_content:
            print("deleted: '%s'" % key)
            both -= key

    for key in po1_content:
        if key not in po0_content:
            print("added: '%s'" % key)
            both -= key

    for key in both:
        msgstr0 = get_msgstr(po0_content[key])
        msgstr1 = get_msgstr(po0_content[key])

        if msgstr0 != msgstr1:
            print("changed: '%s'" % key)
        # else:
        #    print(key + "\n" + msgstr0 + "\n")
