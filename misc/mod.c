int system1(const char *command)
{
    if (system(command)) {
        return 1;
    } else {
        return 0;
    }
}
