"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import {
  resetPasswordSchema,
  type ResetPasswordFormData,
} from "@/lib/validations/auth";

/**
 * Reset-password page.
 *
 * Reached via Supabase recovery flow: the user clicks the email link,
 * hits `/auth/callback?next=/reset-password`, the callback exchanges
 * the code for a session, then lands here. At that point the user is
 * signed in with a recovery session and `updateUser({ password })`
 * rotates the password. We do NOT expose a `token` URL param — the
 * recovery code is single-use and consumed by the callback route.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  async function onSubmit(data: ResetPasswordFormData) {
    setIsLoading(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.updateUser({
        password: data.password,
      });

      if (error) {
        toast.error(
          error.message ||
            "Reset failed. Please request a new link from the forgot-password page.",
        );
        return;
      }

      toast.success("Password reset successfully!");
      // Sign the user out so they re-authenticate with the new password.
      await supabase.auth.signOut();
      router.push("/login");
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="border-border/50">
      <CardHeader className="text-center pb-2">
        <p className="text-sm font-medium tracking-widest text-muted-foreground uppercase mb-2">
          MongoRAG
        </p>
        <CardTitle className="text-3xl font-extralight tracking-tight">
          Reset your password
        </CardTitle>
        <CardDescription className="mt-1">
          Enter your new password below
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="flex flex-col gap-4 pt-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">New password</Label>
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
            <Label htmlFor="confirmPassword">Confirm password</Label>
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              {...register("confirmPassword")}
            />
            {errors.confirmPassword && (
              <p className="text-sm text-destructive">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4 pt-2">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Resetting..." : "Reset password"}
          </Button>
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            Back to sign in
          </Link>
        </CardFooter>
      </form>
    </Card>
  );
}
