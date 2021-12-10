<template>
  <div class="content">
    <h1>Number Pool</h1>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>
    <button v-on:click="initPool">Init Pool</button>
    <button v-on:click="overlayPhoneNumber">Static Overlay</button>
    <button v-on:click="revertOverlay">Revert Overlay</button>
    <button v-on:click="removePoolSession">Remove Session</button>
    <br />
    <a href="tel:+19991231234" data-cta-attr="phone" class="button cta"
      ><span>999-123-1234</span></a
    >
    <br />
    <a href="tel:+19991231234" data-cta-attr="phone" class="button cta"
      ><span>Call 999-123-1234 link</span></a
    >
    <br />
    <a href="tel:+19991231234" data-cta-attr="phone" class="button cta"
      >Call Now</a
    >
    <br />
    <span data-cta-attr="phone" class="button cta">999-123-1234</span>
    <br />
    <span data-cta-attr="phone" class="button cta">Call 999-123-1234 text</span>
    <br />
    <span data-cta-attr="phone" class="button nocta"
      >Call 999-123-1234 no CTA class</span
    >
  </div>
</template>
<script>
export default {
  props: {
    pl: Number,
    poolId: Number
  },
  data: function () {
    return {
      poolInterval: null,
      ctas: null,
      storage: null
    };
  },
  methods: {
    getCTAs: function () {
      return document.querySelectorAll('.cta[data-cta-attr="phone"]');
    },
    initPool: function () {
      console.log("Initiliazing pool:", this.$props.poolId);
      this.$analytics.plugins.zar.initTrackingPool({
        poolId: this.$props.poolId,
        overlayElements: this.ctas,
        renew: false
      });
    },
    overlayPhoneNumber: function () {
      this.$analytics.plugins.zar.overlayPhoneNumber(
        {
          overlayElements: document.querySelectorAll('.nocta[data-cta-attr="phone"]'),
          number: "1234567890"
        }
      );
    },
    revertOverlay: function () {
      this.$analytics.plugins.zar.revertOverlayNumbers({ overlayElements: this.ctas });
    },
    removePoolSession: function () {
      this.$analytics.plugins.zar.removePoolSession({ overlayElements: this.ctas });
    }
  },
  mounted: async function () {
    this.storage = this.$analytics.plugins.zar.getStorage();
    this.ctas = this.getCTAs();
    console.log("Initiliazing pool:", this.$props.poolId);
    const self = this;
    const resp = await this.$analytics.plugins.zar.initTrackingPool({
      poolId: this.$props.poolId,
      overlayElements: this.ctas,
      renew: true,
      renewalInterval: 10 * 1000,
      callback: function (result) {
        self.$analytics.track('number_impressions', { numbers: self.$analytics.plugins.zar.extractPhoneNumbers({ elems: self.ctas }) });
      }
    });
    console.log(resp);
    if (resp) {
      this.poolInterval = resp.interval;
    }
    // Storage may change if server-side cookies override SID/CID
    setTimeout(function () {
      self.storage = self.$analytics.plugins.zar.getStorage();
    }, 1000);
  },
  beforeDestroy() {
    this.revertOverlay();
    if (this.poolInterval) {
      console.log("Clearing interval", this.poolInterval);
      clearInterval(this.poolInterval);
    }
  },
};
</script>
