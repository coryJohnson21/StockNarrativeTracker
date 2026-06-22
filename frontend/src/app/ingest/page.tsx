import { Upload, Youtube, FileText, Zap } from "lucide-react";
import { IngestForm } from "@/components/IngestForm";
import { Card, CardContent } from "@/components/ui/card";

const steps = [
  { icon: Youtube, label: "Ingest", desc: "Paste a YouTube URL or transcript" },
  { icon: Zap, label: "Transcribe", desc: "Whisper AI extracts the audio" },
  { icon: FileText, label: "Extract", desc: "GPT-4o identifies stocks, themes, sentiment" },
  { icon: Upload, label: "Score", desc: "Narrative momentum updated in real-time" },
];

export default function IngestPage() {
  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Upload className="h-7 w-7 text-primary" />
          Add Financial Content
        </h1>
        <p className="text-muted-foreground mt-1">
          Feed in CNBC clips, earnings calls, Bloomberg interviews, or any finance content.
        </p>
      </div>

      {/* How it works */}
      <div className="grid grid-cols-4 gap-3">
        {steps.map(({ icon: Icon, label, desc }, i) => (
          <Card key={label} className="text-center">
            <CardContent className="p-4">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <p className="text-xs font-semibold">{label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <IngestForm />
    </div>
  );
}
