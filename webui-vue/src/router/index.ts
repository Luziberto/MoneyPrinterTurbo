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
      component: () => import('../views/ComingSoonView.vue'),
      props: { titleKey: 'Cockpit Tab Videos' },
    },
    {
      path: '/videos/:id',
      name: 'video-detail',
      component: () => import('../views/ComingSoonView.vue'),
      props: { titleKey: 'Cockpit Tab Videos' },
    },
    { path: '/tarefas', name: 'tarefas', component: () => import('../views/TarefasView.vue') },
    {
      path: '/canais',
      name: 'canais',
      component: () => import('../views/ComingSoonView.vue'),
      props: { titleKey: 'Cockpit Tab Channels' },
    },
    {
      path: '/configuracoes',
      name: 'configuracoes',
      component: () => import('../views/ComingSoonView.vue'),
      props: { titleKey: 'Cockpit Tab Settings' },
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
