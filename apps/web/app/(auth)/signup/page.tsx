"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { signupSchema, type SignupFormData } from "@/lib/validations/auth";

export default function SignupPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
  });

  async function onSubmit(data: SignupFormData) {
    setIsLoading(true);
    try {
      const supabase = createClient();
      const origin = window.location.origin;

      const { error } = await supabase.auth.signUp({
        email: data.email,
        password: data.password,
        options: {
          // Persist the org name in user_metadata; the `handle_new_user`
          // Postgres trigger reads `raw_user_meta_data->>'name'` to seed
          // the tenants row.
          data: { name: data.organizationName },
          emailRedirectTo: `${origin}/auth/callback?next=/onboarding/welcome`,
        },
      });

      if (error) {
        if (error.message.toLowerCase().includes("already")) {
          toast.error("An account with that email already exists.");
        } else {
          toast.error(error.message || "Signup failed");
        }
        return;
      }

      setSubmitted(true);
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  if (submitted) {
    return (
      <Card className="border-border/50">
        <CardHeader className="text-center pb-2">
          <p className="text-sm font-medium tracking-widest text-muted-foreground uppercase mb-2">
            MongoRAG
          </p>
          <CardTitle className="text-3xl font-extralight tracking-tight">
            Check your email
          </CardTitle>
          <CardDescription className="mt-2">
            We&apos;ve sent you a confirmation link. Click it to verify your
            address and finish creating your account.
          </CardDescription>
        </CardHeader>
        <CardFooter className="justify-center pt-2">
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            Back to sign in
          </Link>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="border-border/50">
      <CardHeader className="text-center pb-2">
        <p className="text-sm font-medium tracking-widest text-muted-foreground uppercase mb-2">
          MongoRAG
        </p>
        <CardTitle className="text-3xl font-extralight tracking-tight">
          Create your account
        </CardTitle>
        <CardDescription className="mt-1">
          Get started in minutes
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="flex flex-col gap-4 pt-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">
                {errors.email.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="Minimum 8 characters"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">
                {errors.password.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="organizationName">Organization name</Label>
            <Input
              id="organizationName"
              placeholder="Your company or project name"
              {...register("organizationName")}
            />
            {errors.organizationName && (
              <p className="text-sm text-destructive">
                {errors.organizationName.message}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4 pt-2">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Creating account..." : "Create account"}
          </Button>
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-foreground hover:underline transition-colors"
            >
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
