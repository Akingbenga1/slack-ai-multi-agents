"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";

export function OrgInviteRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/app/team");
  }, [router]);

  return (
    <Card>
      <CardContent className="py-10 text-center text-body-md text-muted-foreground" role="status">
        Opening team management…
      </CardContent>
    </Card>
  );
}
