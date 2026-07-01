const { prebuiltAppConfig } = require("@mlc-ai/web-llm");
console.log("Model List:");
prebuiltAppConfig.model_list.forEach(m => console.log("- " + m.model_id));
