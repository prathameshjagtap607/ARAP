import { SessionProvider } from "@/context/SessionContext";

export default function AssessmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SessionProvider>{children}</SessionProvider>;
}
