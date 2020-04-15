#ifndef API_H
#define API_H

typedef struct HandleImpl HandleStruct;
typedef HandleStruct *Handle;

Handle api_new(void);
void api_use(Handle);
void api_delete(Handle);

#endif /* API_H */
