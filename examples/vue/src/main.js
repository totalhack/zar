import Vue from 'vue'
import App from './App.vue'
import VueRouter from 'vue-router'
import updatePageTags from './utils/updatePageTags'
import routes from './routes'
import { init, getIds } from '../../../frontend/src/zar';

Vue.config.productionTip = false
Vue.use(VueRouter)

const router = new VueRouter({
  mode: 'history', routes
})

const zar = init({
  app: 'my-vue-app',
  gtmContainerId: process.env.VUE_APP_GTM_CONTAINER_ID,
  debug: true,
});

/* Update route title tags & page meta */
router.beforeEach(updatePageTags)

router.afterEach((to, from) => {
  console.log(`Route change to ${to.path} from ${from.path}`) // eslint-disable-line
  console.log(JSON.stringify(getIds()));
  zar.analytics.page()
})

new Vue({
  router,
  render: h => h(App)
}).$mount('#app')

