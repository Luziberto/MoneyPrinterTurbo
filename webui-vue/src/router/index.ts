import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
    {
      path: '/criar',
      name: 'criar',
      component: () => import('../views/CriarView.vue'),
    },
    {
      path: '/videos',
      name: 'videos',
      component: () => import('../views/VideosView.vue'),
    },
    {
      path: '/videos/:id',
      name: 'video-detail',
      component: () => import('../views/VideoDetailView.vue'),
    },
    { path: '/tarefas', name: 'tarefas', component: () => import('../views/TarefasView.vue') },
    {
      path: '/canais',
      name: 'canais',
      component: () => import('../views/CanaisView.vue'),
    },
    {
      path: '/configuracoes',
      name: 'configuracoes',
      component: () => import('../views/ConfiguracoesView.vue'),
    },
    { path: '/config', redirect: '/configuracoes' },
    { path: '/historico', redirect: '/canais' },
    { path: '/topicos', redirect: '/canais' },
    // Legacy per-step wizard URLs -- the wizard no longer changes the route
    // between steps (step is local component state, see CriarView.vue),
    // but old bookmarks/links should still land somewhere useful.
    { path: '/criar/:step', redirect: '/criar' },
  ],
})

export default router
