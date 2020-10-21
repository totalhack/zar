import Home from './components/Home.vue';
import PageOne from './components/PageOne.vue';
import PageTwo from './components/PageTwo.vue';

const routes = [
  {
    path: '/',
    component: Home,
    meta: {
      title: 'Home Page',
    }
  },
  {
    path: '/one',
    component: PageOne,
    meta: {
      title: 'Page One',
    }
  },
  {
    path: '/two',
    component: PageTwo,
    meta: {
      title: 'Page Two',
    }
  },
];

export default routes;
