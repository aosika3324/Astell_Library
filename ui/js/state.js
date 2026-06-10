export const state = {
    pendingData: [],
    selectedIndex: -1,
    activeView: 'tasks',
    logInterval: null,
    selectedTaskId: null,
    selectedTaskTitle: "",
    activeTaskTab: 'terminal',
    expandedPaths: new Set(),
    libraryTreeData: [],
    workspaceModules: [],
    selectedWsIndex: -1
};