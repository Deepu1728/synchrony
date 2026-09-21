export type User = { username: string; role: string };

export type Token = {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: string;
};
