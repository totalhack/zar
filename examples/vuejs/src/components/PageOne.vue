<template>
  <div class="content">
    <h1>Page One</h1>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>
  </div>
</template>
<script>
export default {
  data: function () {
    return {
      storage: null
    };
  },
  mounted: function () {
    this.storage = this.$analytics.plugins.zar.getStorage();
  }
};
</script>
