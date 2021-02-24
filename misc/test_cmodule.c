#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *TestCModuleError;

static PyObject *
test_cmodule_system(PyObject *self, PyObject *args)
{
    const char *command;
    int sts;

    if (!PyArg_ParseTuple(args, "s", &command))
        return NULL;

    sts = system(command);
    if (sts < 0) {
        PyErr_SetString(TestCModuleError, "System command failed");
        return NULL;
    }

    return PyLong_FromLong(sts);
}

static PyMethodDef test_cmodule_functions[] = {
    {"system",  test_cmodule_system, METH_VARARGS, "Execute a shell command."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef test_cmodule = {
    PyModuleDef_HEAD_INIT,
    "test_cmodule",   /* name of module */
    "Simple C module", /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    test_cmodule_functions
};

PyMODINIT_FUNC
PyInit_test_cmodule(void)
{
    PyObject *m;

    m = PyModule_Create(&test_cmodule);
    if (m == NULL)
        return NULL;

    TestCModuleError = PyErr_NewException("test_cmodule.TestCModuleError",
            NULL, NULL);
    Py_XINCREF(TestCModuleError);
    if (PyModule_AddObject(m, "error", TestCModuleError) < 0) {
        Py_XDECREF(TestCModuleError);
        Py_CLEAR(TestCModuleError);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
