<template>
  <div class="content">
    <h1>Page Two</h1>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>
  </div>
</template>
<script>
export default {
  computed: {
    storage: function () {
      return this.$analytics.plugins.zar.getStorage();
    }
  }
}
</script>
