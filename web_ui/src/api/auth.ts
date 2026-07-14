import client from "./client";

export const authApi = {
  login: (username: string, password: string) =>
    client.post("/api/auth/login", { username, password }),
  register: (username: string, password: string) =>
    client.post("/api/auth/register", { username, password }),
};
