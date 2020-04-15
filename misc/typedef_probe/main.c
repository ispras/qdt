#include "api.h"

void main() {
    Handle h = api_new();
    api_use(h);
    api_delete(h);
}
