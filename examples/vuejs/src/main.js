import Vue from "vue";
import App from "./App.vue";
import VueRouter from "vue-router";
import updatePageTags from "./utils/updatePageTags";
import routes from "./routes";
import { init } from "../../../frontend/src/zar";
// To test from built dist bundle:
// import { init } from '../../../frontend/dist/zar.umd.js';

Vue.config.productionTip = false;
Vue.use(VueRouter);

const router = new VueRouter({
  mode: "history",
  routes
});

const analytics = init({
  app: "my-vue-app",
  ga4Config: {
    trackingId: process.env.VUE_APP_GA4_TRACKING_ID,
    customDimensions: [
      {
        name: "vid",
        callback: function (instance, config) {
          return instance.plugins.zar.getVID();
        }
      }
    ]
  },
  facebookConfig: {
    trackingId: process.env.VUE_APP_FACEBOOK_PIXEL_ID
  },
  apiUrl: "http://localhost/api/v2",
  poolConfig: {
    // poolId: 1, // Setting global pool ID is optional
    // poolId: function () { return 1 },
    poolId: function () {
      return window.zarPoolId;
    },
    overlayQuerySelector: '.cta[data-cta-attr="phone"]',
    renewalInterval: 10 * 1000,
    initCallback: function (x) {
      console.log("init callback!", x);
    },
    contextCallback: function (currentContext) {
      var context = { url: window.location.href };
      if (currentContext) {
        context = Object.assign({}, currentContext, context);
      }
      console.log("context callback!", context);
      return context;
    }
  }
});

Vue.prototype.$analytics = analytics;
Vue.prototype.window = window;

router.beforeEach(updatePageTags);

router.afterEach((to, from) => {
  console.log(`Route change to ${to.path} from ${from.path}`);
  // Wait for components to be created so route props are available
  Vue.nextTick(() => {
    analytics.page();
  });
});

new Vue({
  router,
  render: (h) => h(App)
}).$mount("#app");
