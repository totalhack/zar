<template>
  <div class="content">
    <h1>Number Pool</h1>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>

    <button v-on:click="overlayPhoneNumber">Static Overlay</button>
    <button v-on:click="revertOverlay">Revert Overlay</button>
    <button v-on:click="clearPoolIntervals">Clear Intervals</button>
    <button v-on:click="updateNumberContext">Update Context</button>
    <button v-on:click="updateContextVar">Update Context Var</button>

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
    <a
      data-cta-attr="phone"
      href="tel:+19991231234"
      class="button cta button-w-icon hero-btn phone w-inline-block"
      ><img
        src="https://assets.website-files.com/62ade83a1a672b0b0eafa33d/62b55349ae2b454b71f603bc_phone.svg"
        loading="lazy"
        alt=""
        class="btn-icon hero-btn"
      />
      <div class="text-block-3">999-123-1234</div>
    </a>
    <br />
    <span data-cta-attr="phone" class="button cta">999-123-1234</span>
    <br />
    <span data-cta-attr="phone" class="button cta">Call 999-123-1234 text</span>
    <br />
    <span data-cta-attr="phone" class="button nocta"
      >Call 999-123-1234 no CTA class</span
    >
    <pre>{{ JSON.stringify(poolStats, null, 2) }}</pre>
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
      ctas: null,
      storage: null,
      poolStats: null
    };
  },
  methods: {
    getCTAs: function () {
      return document.querySelectorAll('.cta[data-cta-attr="phone"]');
    },
    overlayPhoneNumber: function () {
      this.$analytics.plugins.zar.overlayPhoneNumber({
        overlayElements: document.querySelectorAll(
          '.nocta[data-cta-attr="phone"]'
        ),
        number: "1234567890"
      });
    },
    revertOverlay: function () {
      this.$analytics.plugins.zar.revertOverlayNumbers({
        overlayElements: this.ctas
      });
    },
    clearPoolInterval: function () {
      console.log("clear interval", this.$props.poolId);
      this.$analytics.plugins.zar.clearPoolInterval({
        poolId: this.$props.poolId
      });
    },
    clearPoolIntervals: function () {
      console.log("clear intervals");
      this.$analytics.plugins.zar.clearPoolIntervals();
    },
    updateNumberContext: function () {
      this.$analytics.plugins.zar.updateTrackingNumberContext({
        number: window.zarPoolData.number,
        context: { test: new Date().toLocaleTimeString() }
      });

      this.$nextTick(() => {
        this.refreshStats();
      });
    },
    updateContextVar: function () {
      var date = new Date().toLocaleTimeString();
      window.zarPoolDataLayer.push({ [date]: date });
      this.$nextTick(() => {
        this.refreshStats();
      });
    },
    refreshStats: async function () {
      this.poolStats = await this.$analytics.plugins.zar.getPoolStats({
        with_contexts: true
      });
    }
  },
  created: function () {
    // Earliest point where props are available in Vue 2
    if (this && this.window) {
      this.window.zarPoolId = this.$props.poolId;
    } else if (typeof window !== "undefined") {
      window.zarPoolId = this.$props.poolId;
    }
  },
  mounted: async function () {
    this.window.zarPoolId = this.$props.poolId;
    console.log("Initiliazing pool:", this.$props.poolId);
    this.storage = this.$analytics.plugins.zar.getStorage();
    this.ctas = this.getCTAs();
    this.refreshStats();
  },
  beforeDestroy() {
    this.revertOverlay();
    this.clearPoolInterval();
    this.window.zarPoolId = null;
  }
};
</script>

<style scoped>
.btn-icon.hero-btn {
  margin-right: 10px;
}

.btn-icon {
  width: 30px;
  height: 30px;
  margin-right: 20px;
  -webkit-filter: invert(100%);
  filter: invert(100%);
}

img {
  border: 0;
  vertical-align: middle;
  display: inline-block;
  max-width: 100%;
}

.button-w-icon {
  display: -webkit-box;
  display: -webkit-flex;
  display: -ms-flexbox;
  display: flex;
  margin-bottom: 16px;
  padding: 24px 16px;
  -webkit-box-pack: center;
  -webkit-justify-content: center;
  -ms-flex-pack: center;
  justify-content: center;
  -webkit-box-align: center;
  -webkit-align-items: center;
  -ms-flex-align: center;
  align-items: center;
  border: 1.5px #1f3584;
  border-radius: 8px;
  background-color: #1f3584;
  -webkit-transition: border-color 0.3s, color 0.3s, background-color 0.3s,
    -webkit-transform 0.3s;
  transition: transform 0.3s, border-color 0.3s, color 0.3s,
    background-color 0.3s, -webkit-transform 0.3s;
  color: #fff;
  line-height: 20px;
  font-weight: 700;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}

.w-inline-block {
  max-width: 200px;
}
</style>
