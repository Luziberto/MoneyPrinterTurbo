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
    { path: '/canais', name: 'canais', component: () => import('../views/CanaisView.vue') },
    { path: '/tarefas', name: 'tarefas', component: () => import('../views/TarefasView.vue') },
    { path: '/config', name: 'config', component: () => import('../views/ConfigView.vue') },
  ],
})

export default router
