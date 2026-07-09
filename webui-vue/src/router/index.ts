import { createRouter, createWebHistory } from 'vue-router'
import { STEP_IDS } from '../types/workspace'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/criar/script' },
    {
      path: '/criar/:step',
      name: 'criar',
      component: () => import('../views/CriarView.vue'),
      props: true,
      beforeEnter: (to) => {
        if (!STEP_IDS.includes(to.params.step as (typeof STEP_IDS)[number])) {
          return '/criar/script'
        }
      },
    },
    { path: '/historico', name: 'historico', component: () => import('../views/HistoricoView.vue') },
    { path: '/topicos', redirect: '/historico' },
    { path: '/canais', redirect: '/criar/script' },
    { path: '/tarefas', name: 'tarefas', component: () => import('../views/TarefasView.vue') },
    { path: '/config', redirect: '/' },
  ],
})

export default router
