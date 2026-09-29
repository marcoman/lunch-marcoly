import { createApp } from "vue";
import { LDPlugin } from "launchdarkly-vue-client-sdk";
import App from "./App.vue";
import "./styles.css";

const app = createApp(App);
app.use(LDPlugin, { deferInitialization: true });
app.mount("#app");
