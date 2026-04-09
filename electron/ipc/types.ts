export interface IPCResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}
