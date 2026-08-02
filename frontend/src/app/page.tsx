import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground p-6 md:p-12 flex flex-col items-center justify-center">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">ColdTrack AI</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Early Warning System for Cold Chain Logistics — COMPFEST 18
            </p>
          </div>
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 px-3 py-1 text-xs">
            ● System Active
          </Badge>
        </div>

        {/* Info Alert */}
        <Alert className="border-primary/20 bg-primary/5">
          <AlertTitle className="font-semibold text-primary">Frontend Initialized</AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground mt-1">
            Next.js 14 App Router, TypeScript, Tailwind CSS, and shadcn/ui have been configured.
          </AlertDescription>
        </Alert>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">FastAPI Backend Connection</CardTitle>
              <CardDescription className="text-xs">Synchronous REST API Service</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-3">
                Configured to communicate with FastAPI at port 8000.
              </p>
              <Button size="sm" variant="outline" className="w-full">
                Check Health API
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">ONNX GRU Inference Engine</CardTitle>
              <CardDescription className="text-xs">Multi-head Sequence Prediction</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-3">
                Predicts cold chain failures in real-time.
              </p>
              <Button size="sm" variant="default" className="w-full">
                Run Simulation
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
