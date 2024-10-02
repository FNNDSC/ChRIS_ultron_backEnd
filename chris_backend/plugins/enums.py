
# front-end API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values"), ("unextpath", "Unextracted path values")]

# table of equivalence between front-end API types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path', 'unextpath': 'unextpath'}

PLUGIN_TYPE_CHOICES = [("ds", "Data synthesis"), ("fs", "Feed synthesis"),
                       ("ts", "Topology synthesis")]
