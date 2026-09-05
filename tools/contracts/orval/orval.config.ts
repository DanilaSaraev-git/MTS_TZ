import { defineConfig } from "orval";

export default defineConfig({
  reviewPlatform: {
    input: "../../../contracts/review-platform/v1/openapi.yaml",
    output: {
      target: "./generated/review-platform.ts",
      client: "fetch",
      clean: true,
      prettier: false,
    },
  },
});
