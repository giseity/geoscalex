import type { ReactNode } from "react"
import { Beaker, Boxes, FileUp } from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type DatasetDataViewProps = {
  importView: ReactNode
  generateView: ReactNode
  versionsView: ReactNode
}

export function DatasetDataView({ importView, generateView, versionsView }: DatasetDataViewProps) {
  return (
    <Tabs className="min-h-[calc(100vh-65px)] gap-0" defaultValue="import">
      <div className="sticky top-[65px] z-10 border-b bg-background/92 px-4 py-3 backdrop-blur lg:px-6">
        <div className="mx-auto flex max-w-6xl items-center gap-4">
          <div className="min-w-0 flex-1"><p className="text-sm font-semibold">Dataset data</p><p className="text-xs text-muted-foreground">Ingest, synthesize, and publish</p></div>
          <TabsList>
            <TabsTrigger value="import"><FileUp /> Import</TabsTrigger>
            <TabsTrigger value="generate"><Beaker /> Generate</TabsTrigger>
            <TabsTrigger value="versions"><Boxes /> Versions</TabsTrigger>
          </TabsList>
        </div>
      </div>
      <TabsContent value="import">{importView}</TabsContent>
      <TabsContent value="generate">{generateView}</TabsContent>
      <TabsContent value="versions">{versionsView}</TabsContent>
    </Tabs>
  )
}
