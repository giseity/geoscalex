import { Fragment } from "react"
import { ChevronsUpDown, CircleDot, Database, GitCompareArrows, Layers3, MapPinned, Plus } from "lucide-react"

import { GeometryThumbnail } from "@/components/geometry-stage"
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
import type { Batch, Dataset, Feature, Workspace } from "@/lib/api"

export type LabView = "datasets" | "workbench" | "review" | "data"

export type DatasetGroup = {
  workspace: Workspace
  datasets: Dataset[]
}

type LabSidebarProps = {
  datasetGroups: DatasetGroup[]
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
  { id: "datasets" as const, label: "Datasets", icon: Database },
  { id: "workbench" as const, label: "Workbench", icon: GitCompareArrows },
  { id: "review" as const, label: "Review queue", icon: MapPinned },
  { id: "data" as const, label: "Data", icon: Layers3 },
]

export function LabSidebar({
  datasetGroups,
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
  const activeWorkspace = datasetGroups.find((group) => group.workspace.id === dataset.workspace_id)?.workspace
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
                <span className="block truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/55">{activeWorkspace?.name ?? "Dataset"}</span>
                <span className="block truncate font-semibold">{dataset.name}</span>
              </span>
              <ChevronsUpDown className="size-4 opacity-50" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-[70vh] w-72 overflow-y-auto">
            {datasetGroups.map((group, index) => (
              <Fragment key={group.workspace.id}>
                {index > 0 && <DropdownMenuSeparator />}
                <DropdownMenuLabel>{group.workspace.name}</DropdownMenuLabel>
                {group.datasets.map((item) => (
                  <DropdownMenuItem className={item.id === dataset.id ? "bg-accent" : undefined} key={item.id} onClick={() => onDatasetChange(item)}>
                    <Database />
                    <span className="min-w-0">
                      <span className="block truncate">{item.name}</span>
                      {item.description && <span className="block truncate text-[11px] text-muted-foreground">{item.description}</span>}
                    </span>
                  </DropdownMenuItem>
                ))}
                {!group.datasets.length && <p className="px-2 py-2 text-xs text-muted-foreground">No datasets</p>}
              </Fragment>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
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
                        isActive={feature.id === selectedFeatureId && view === "workbench"}
                        onClick={() => {
                          onFeatureChange(feature)
                          onViewChange("workbench")
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
              {!features.length && <li className="px-2 py-8 text-center text-xs leading-5 text-muted-foreground">Draw, import, or generate your first geometry.</li>}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/70 p-3 group-data-[collapsible=icon]:p-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground group-data-[collapsible=icon]:justify-center">
          <CircleDot className="size-3 fill-emerald-500 text-emerald-600" />
          <span className="group-data-[collapsible=icon]:hidden">Local · SQLite</span>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
