import { useChannelsStore } from '../stores/channels'
import { useDashboardStore } from '../stores/dashboard'
import { useWorkspaceStore } from '../stores/workspace'

export function useActiveChannelSwitch() {
  const channelsStore = useChannelsStore()
  const workspaceStore = useWorkspaceStore()
  const dashboardStore = useDashboardStore()

  async function switchChannel(slug: string) {
    if (!slug || slug === channelsStore.activeSlug) return
    channelsStore.setActiveChannel(slug)
    dashboardStore.closeProvider()
    await workspaceStore.load(slug)
    await dashboardStore.refresh()
  }

  return { switchChannel }
}
