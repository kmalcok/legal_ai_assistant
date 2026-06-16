import { SignupForm } from "@/components/signup-form"

export function RegisterPage() {
  return (
    <div className="auth-page-shell flex min-h-svh flex-col items-center justify-center bg-muted p-4 md:p-6 lg:p-8">
      <div className="w-full max-w-sm md:max-w-4xl lg:max-w-5xl 2xl:max-w-6xl transition-all duration-300">
        <SignupForm />
      </div>
    </div>
  )
}
