import { Fragment } from "react"
import {
  Beaker,
  Boxes,
  ChevronsUpDown,
  Database,
  FileUp,
  GitCompareArrows,
  Layers3,
  MapPinned,
  Plus,
  Settings2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import type { Batch, Dataset, Feature } from "@/lib/api"
import { GeometryThumbnail } from "@/components/geometry-stage"

export type LabView = "compare" | "generate" | "import" | "versions"

type LabSidebarProps = {
  datasets: Dataset[]
  dataset: Dataset
  batches: Batch[]
  features: Feature[]
  selectedFeatureId: string | null
  view: LabView
  onDatasetChange: (dataset: Dataset) => void
  onFeatureChange: (feature: Feature) => void
  onViewChange: (view: LabView) => void
  onNewFeature: () => void
}

const navigation = [
  { id: "compare" as const, label: "Compare", icon: GitCompareArrows },
  { id: "generate" as const, label: "Generate", icon: Beaker },
  { id: "import" as const, label: "Import", icon: FileUp },
  { id: "versions" as const, label: "Versions", icon: Boxes },
]

export function LabSidebar({
  datasets,
  dataset,
  batches,
  features,
  selectedFeatureId,
  view,
  onDatasetChange,
  onFeatureChange,
  onViewChange,
  onNewFeature,
}: LabSidebarProps) {
  const groups = [
    ...batches.map((batch) => ({ id: batch.id, name: batch.name, features: features.filter((feature) => feature.batch_id === batch.id) })),
    { id: "manual", name: "Manual", features: features.filter((feature) => !feature.batch_id) },
  ].filter((group) => group.features.length)

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="border-b border-sidebar-border/70 p-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton className="h-12" size="lg">
              <span className="grid size-8 place-items-center rounded-lg bg-[#00796f] text-white"><MapPinned className="size-4" /></span>
              <span className="min-w-0 flex-1 text-left">
                <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/55">Dataset</span>
                <span className="block truncate font-semibold">{dataset.name}</span>
              </span>
              <ChevronsUpDown className="size-4 opacity-50" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel>Local datasets</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {datasets.map((item) => (
              <DropdownMenuItem key={item.id} onClick={() => onDatasetChange(item)}>
                <Database /> {item.name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Lab</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navigation.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton isActive={view === item.id} onClick={() => onViewChange(item.id)} tooltip={item.label}>
                    <item.icon /> <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup className="min-h-0 flex-1 group-data-[collapsible=icon]:hidden">
          <div className="mb-1 flex items-center justify-between pr-1">
            <SidebarGroupLabel>Features · {features.length}</SidebarGroupLabel>
            <Button aria-label="Draw geometry" onClick={onNewFeature} size="icon-sm" variant="ghost"><Plus /></Button>
          </div>
          <SidebarGroupContent className="overflow-y-auto">
            <SidebarMenu>
              {groups.map((group) => (
                <Fragment key={group.id}>
                  <li className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">{group.name} · {group.features.length}</li>
                  {group.features.map((feature) => (
                    <SidebarMenuItem key={feature.id}>
                      <SidebarMenuButton
                        className="h-12"
                        isActive={feature.id === selectedFeatureId}
                        onClick={() => {
                          onFeatureChange(feature)
                          onViewChange("compare")
                        }}
                      >
                        <GeometryThumbnail geometry={feature.current_revision.geometry} />
                        <span className="min-w-0">
                          <span className="block truncate text-sm">{feature.name}</span>
                          <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">{feature.current_revision.geometry.type}</span>
                        </span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </Fragment>
              ))}
              {!features.length && (
                <li className="px-2 py-8 text-center text-xs leading-5 text-muted-foreground">
                  Draw, import, or generate your first geometry.
                </li>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/70">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Local storage"><Layers3 /><span>Local storage</span></SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Settings"><Settings2 /><span>Settings</span></SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
