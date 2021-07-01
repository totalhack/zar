<template>
  <div id="app">
    <div class="header">
      <nav>
        <router-link to="/">Home</router-link>
        <router-link to="/one">Page One</router-link>
        <router-link to="/two">Page Two</router-link>
        <router-link
          key="number-pool-1"
          :to="{ name: 'number-pool-1', query: { pl: 1 } }"
          >Number Pool 1</router-link
        >
        <router-link
          key="number-pool-2"
          :to="{ name: 'number-pool-2', query: { pl: 1 } }"
          >Number Pool 2</router-link
        >
        <router-link to="/number-pool-stats">Number Pool Stats</router-link>
        <a href="http://localhost:8080/">Regular Link Home</a>
      </nav>
    </div>
    <router-view :key="$route.fullPath"></router-view>
  </div>
</template>

<script>
export default {};
</script>

<style>
html,
body {
  height: 100%;
  width: 100%;
  padding: 0;
  margin: 0;
  background: #fafafa;
  font-family: "Helvetica Neue", arial, sans-serif;
  font-weight: 400;
  color: #444;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

#app {
  height: 100%;
}

.content {
  padding: 56px 20px;
  min-height: 100%;
  width: 100%;
}

.header {
  position: fixed;
  left: 0;
  top: 0;
  width: 100%;
  height: 56px;
  padding: 0;
  background: #673ab7;
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.5);
  z-index: 50;
}

.header h1 {
  float: left;
  margin: 0;
  padding: 0 15px;
  font-size: 24px;
  line-height: 56px;
  font-weight: 400;
  color: #fff;
}

.header nav {
  font-size: 100%;
}

.header nav a {
  display: inline-block;
  height: 56px;
  line-height: 56px;
  padding: 0 15px;
  min-width: 50px;
  text-align: center;
  background: rgba(255, 255, 255, 0);
  text-decoration: none;
  color: #fff;
  will-change: background-color;
}

.header nav a:hover,
.header nav a:active {
  background: rgba(0, 0, 0, 0.2);
}

.header nav a.active {
  background: rgba(0, 0, 0, 0.4);
}
</style>
