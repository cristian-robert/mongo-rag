import "next-auth";

declare module "next-auth" {
  interface User {
    tenant_id: string;
    role: string;
  }

  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      tenant_id: string;
      role: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    tenant_id?: string;
    role?: string;
  }
}
