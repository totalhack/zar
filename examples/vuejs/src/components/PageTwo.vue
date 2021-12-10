<template>
  <div class="content">
    <h1>Page Two</h1>
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
    // Storage may change if server-side cookies override SID/CID
    var self = this;
    setTimeout(function () {
      self.storage = self.$analytics.plugins.zar.getStorage();
    }, 1000);
  }
};
</script>
