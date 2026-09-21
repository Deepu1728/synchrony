import { api } from "./client";
import type { Token, User } from "./types";

export const requestLogin = (username: string, password: string) =>
  api<Token>("/auth/login", { method: "POST", form: { username, password } });

export const fetchMe = () => api<User>("/auth/me");
