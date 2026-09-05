import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import SwaggerParser from "@apidevtools/swagger-parser";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import YAML from "yaml";

const root = path.resolve(import.meta.dirname, "../../..");
const contractRoot = path.join(root, "contracts/review-platform/v1");
const internalRoot = path.join(root, "specs/003-backend-implementation/contracts");
const openapiPath = path.join(contractRoot, "openapi.yaml");

const source = fs.readFileSync(openapiPath, "utf8");
const parsedDocument = YAML.parseDocument(source, { uniqueKeys: true });
if (parsedDocument.errors.length) {
  throw new Error(parsedDocument.errors.map((error) => error.message).join("; "));
}
const openapi = parsedDocument.toJS();
await SwaggerParser.validate(openapiPath);

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);

const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"), (key, value, context) => {
  if (context?.source === undefined) return value;
  return value;
});

const validate = (schema, value, label) => {
  const validator = ajv.compile(schema);
  if (!validator(value)) {
    throw new Error(`${label}: ${ajv.errorsText(validator.errors, { separator: "; " })}`);
  }
};

const skillExamples = {
  "review-input.json": "review-input.schema.json",
  "review-output.json": "review-output.schema.json",
  "finding-dialogue-input.json": "finding-dialogue-input.schema.json",
  "finding-dialogue-output.json": "finding-dialogue-output.schema.json",
  "skill-manifest.json": "skill-manifest.schema.json",
};
for (const [exampleName, schemaName] of Object.entries(skillExamples)) {
  validate(
    readJson(path.join(contractRoot, "schemas", schemaName)),
    readJson(path.join(contractRoot, "examples/skill", exampleName)),
    exampleName,
  );
}

const httpExamples = {
  "bootstrap.json": "Bootstrap",
  "document.json": "Document",
  "profiles.json": null,
  "model-profiles.json": null,
  "create-review-run.json": "CreateReviewRun",
  "review-run.queued.json": "ReviewRun",
  "review-run.completed.json": "ReviewRun",
  "review-run.failed.json": "ReviewRun",
  "report.json": "ReviewReport",
  "report.partial.json": "ReviewReport",
  "finding-states.json": "FindingStateList",
  "dialogue.open.json": "FindingDialogue",
  "dialogue.generating.json": "FindingDialogue",
  "dialogue.failed.json": "FindingDialogue",
  "create-dialogue-turn.json": "CreateDialogueTurn",
  "retry-dialogue-turn.json": "RetryDialogueTurn",
  "decision.json": "HumanDecision",
  "put-decision.json": "PutFindingDecision",
  "problem.json": "Problem"
};
for (const [exampleName, componentName] of Object.entries(httpExamples)) {
  const value = readJson(path.join(contractRoot, "examples/http", exampleName));
  if (!componentName) continue;
  validate({
    $schema: "https://json-schema.org/draft/2020-12/schema",
    $ref: `#/components/schemas/${componentName}`,
    components: openapi.components,
  }, value, exampleName);
}

for (const schemaName of [
  "job-envelope.v1.schema.json",
  "poc-import-view.v1.schema.json",
  "runtime-config.v1.schema.json",
  "trusted-fixture-expected-output.v1.schema.json",
]) {
  const schema = readJson(path.join(internalRoot, schemaName));
  ajv.compile(schema);
}

if (openapi.info.version !== "1.0.2") throw new Error("OpenAPI version must be 1.0.2");
if (openapi.security?.length !== 0 || openapi.components?.securitySchemes) {
  throw new Error("No-auth v1 must not publish security schemes");
}
const serialized = JSON.stringify(openapi);
if (/\"401\"|\"403\"/.test(serialized)) throw new Error("No-auth v1 must not publish 401/403 responses");

console.log("contract schemas, references, examples, and no-auth boundary: ok");
