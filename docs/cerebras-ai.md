max_completion_tokens
integer | null
The maximum number of tokens that can be generated in the completion. The total length of input tokens and generated tokens is limited by the model’s context length.
​
response_format
object | null
Controls the format of the model response. The primary option is structured outputs with schema enforcement, which ensures the model returns valid JSON adhering to your defined schema structure.
Setting to { "type": "json_schema", "json_schema": { "name": "schema_name", "strict": true, "schema": {...} } } enforces schema compliance. The schema must follow standard JSON Schema format with the following properties:
Show json_schema properties

Note: Structured outputs with JSON schema is currently in beta. Visit our page on Structured Outputs for more information.
Show JSON mode

​
seed
integer | null
If specified, our system will make a best effort to sample deterministically, such that repeated requests with the same seed and parameters should return the same result. Determinism is not guaranteed.
​
stop
string | null
Up to 4 sequences where the API will stop generating further tokens. The returned text will not contain the stop sequence.
​
stream
boolean | null
If set, partial message deltas will be sent.
​
temperature
number | null
What sampling temperature to use, between 0 and 1.5. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. We generally recommend altering this or top_p but not both.
​
top_p
number | null
An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So, 0.1 means only the tokens comprising the top 10% probability mass are considered. We generally recommend altering this or temperature but not both.
​
tool_choice
string | object
Controls which (if any) tool is called by the model. none means the model will not call any tool and instead generates a message. auto means the model can pick between generating a message or calling one or more tools. required means the model must call one or more tools. Specifying a particular tool via {"type": "function", "function": {"name": "my_function"}} forces the model to call that tool.
none is the default when no tools are present. auto is the default if tools are present.
​
tools
object | null
A list of tools the model may call. Currently, only functions are supported as a tool. Use this to provide a list of functions the model may generate JSON inputs for.
Specifying tools consumes prompt tokens in the context. If too many are given, the model may perform poorly or you may hit context length limitations
Show properties

​
user
string | null
A unique identifier representing your end-user, which can help to monitor and detect abuse.
​
logprobs
bool
Whether to return log probabilities of the output tokens or not.
Default: False
​
top_logprobs
integer | null
An integer between 0 and 20 specifying the number of most likely tokens to return at each token position, each with an associated log probability. logprobs must be set to true if this parameter is used.

Completions

Copy page

​
Completion Request
​
prompt
string | array
The prompt(s) to generate completions for, encoded as a string, array of strings, array of tokens, or array of token arrays. Default: ""
​
model
stringrequired
Available options:
qwen-3-235b-a22b-instruct-2507
llama3.1-8b
llama-3.3-70b
llama-4-maverick-17b-128e-instruct
qwen-3-32b
qwen-3-235b-a22b
llama-4-scout-17b-16e-instruct
deepseek-r1-distill-llama-70b (private preview)
​
stream
boolean | null
If set, partial message deltas will be sent. Tokens will be sent as data-only server-sent events as they become available, with the stream terminated by a data: [DONE] message. Default: false
​
return_raw_tokens
boolean | null
Return raw tokens instead of text. Default: false
​
max_tokens
integer | null
The maximum number of tokens that can be generated in the chat completion. The total length of input tokens and generated tokens is limited by the model’s context length. Default: null
​
min_tokens
integer | null
The minimum number of tokens to generate for a completion. If not specified or set to 0, the model will generate as many tokens as it deems necessary. Setting to -1 sets to max sequence length. Default: null
​
grammar_root
string | null
The grammar root used for structured output generation. Supported values: root, fcall, nofcall, insidevalue, value, object, array, string, number, funcarray, func, ws. Default: null
​
seed
integer | null
If specified, our system will make a best effort to sample deterministically, such that repeated requests with the same seed and parameters should return the same result. Determinism is not guaranteed. Default: null
​
stop
string | array | null
Up to 4 sequences where the API will stop generating further tokens. The returned text will not contain the stop sequence. Default: null
​
temperature
float | null
What sampling temperature to use, between 0 and 1.5. Higher values (e.g., 0.8) will make the output more random, while lower values (e.g., 0.2) will make it more focused and deterministic. We generally recommend altering this or top_p but not both. Default: 1.0
​
top_p
float | null
An alternative to sampling with temperature, called nucleus sampling, where the model considers the tokens with top_p probability mass. For example, 0.1 means only the tokens comprising the top 10% probability mass are considered. We generally recommend altering this or temperature but not both. Default: 1.0
​
echo
boolean
Echo back the prompt in addition to the completion. Incompatible with return_raw_tokens=True. Default: false
​
user
string | null
A unique identifier representing your end-user, which can help Cerebras to monitor and detect abuse. Default: null
​
Completion Response
​
choices
object[]required
The list of completion choices the model generated for the input prompt.
Show properties

​
created
integer | nullrequired
The Unix timestamp (in seconds) of when the completion was created.
​
id
string
A unique identifier for the completion.
​
model
string
The model used for completion.
​
object
stringrequired
The object type, which is always “text_completion”
​
system_fingerprint
string
This fingerprint represents the backend configuration that the model runs with.
Can be used in conjunction with the seed request parameter to understand when backend changes have been made that might impact determinism.
​
usage
object
Usage statistics for the completion request.

list
GET https://api.cerebras.ai/v1/models
Lists the currently available models and provides essential details about each, including the owner and availability.
​
retrieve
GET https://api.cerebras.ai/v1/models/{model}
Fetches a model instance, offering key details about the model, including its owner and permissions.
Accepts model IDs as arguments.
Available options:
qwen-3-235b-a22b-instruct-2507
llama3.1-8b
llama-3.3-70b
llama-4-maverick-17b-128e-instruct
qwen-3-32b
qwen-3-235b-a22b
llama-4-scout-17b-16e-instruct
deepseek-r1-distill-llama-70b (private preview)