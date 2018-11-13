__all__ = [
    "Features"
]


class Features(object):
    """ Helper for `qSupported` packet.
    """

    def __init__(self, features = {}, **kwfeatures):
        """
    :param features:
        - use `True`/`False` for boolean features (those who are encoded
        using as `name+` and `name-`).
        - use strings for features with values (encoded as `name=value`)

    :param kwfeatures:
        A way to specify features as object instantiation arguments. If a
        feature name is not comply with Python syntax then it may be
        given through `features`.

There is `name?` stub feature encoding form. It results in `None` in
`stubfeatures` after parsing. Support for those features should be detected
using other way.
        """

        kwfeatures.update(features)
        self.gdbfeatures = kwfeatures

        self.stubfeatures = None

    def response(self):
        return ";".join(
            (
                name + (
                    "+" if value is True else (
                        "-" if value is False else (
                            "=" + value
                        )
                    )
                )
            ) for name, value in self.gdbfeatures.items()
        )

    def query(self):
        values = self.response()
        if values:
            return "qSupported:" + values
        else:
            return "qSupported"

    def parse(self, reply):
        self.stubfeatures = features = {}

        for feature in reply.split(";"):
            if feature[-1] == "+":
                features[feature[:-1]] = True
            elif feature[-1] == "-":
                features[feature[:-1]] = False
            elif feature[-1] == "?":
                features[feature[:-1]] = None
            else:
                name, value = feature.split("=")
                features[name] = value

    def __getitem__(self, feature_name):
        """ dict-like access to stub features"
        """
        return self.stubfeatures[feature_name]
