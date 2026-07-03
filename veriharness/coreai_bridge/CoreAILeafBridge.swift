import Foundation
import FoundationModels

struct BridgeRequest: Codable {
    var taskId: String?
    var taskFamily: String?
    var prompt: String
    var instructions: String?
    var maxTokens: Int?
    var temperature: Double?
    var seed: UInt64?
    var availabilityOnly: Bool?
}

struct BridgeResponse: Codable {
    var ok: Bool
    var content: String?
    var error: String?
    var availability: String
}

struct EvidenceRefOut: Codable {
    var source: String
    var locator: String = ""
    var quote: String = ""
    var metadata: [String: String] = [:]
}

struct ClaimOut: Codable {
    var claim: String
    var evidence_refs: [EvidenceRefOut]
    var confidence: Double = 0.7
    var metadata: [String: String] = [:]
}

struct LeafOutputOut: Codable {
    var task_id: String
    var answer: String
    var artifacts: [String]
    var claims: [ClaimOut]
    var self_assessment: [String: String]
    var done: Bool
}

func emit(_ response: BridgeResponse) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try! encoder.encode(response)
    print(String(data: data, encoding: .utf8)!)
}

func encodeLeaf(
    taskId: String,
    answerJson: String,
    artifact: String,
    claim: String
) throws -> String {
    let leaf = LeafOutputOut(
        task_id: taskId,
        answer: answerJson,
        artifacts: [artifact],
        claims: [
            ClaimOut(
                claim: claim,
                evidence_refs: [
                    EvidenceRefOut(
                        source: "FoundationModels structured generation",
                        quote: answerJson
                    )
                ]
            )
        ],
        self_assessment: ["structured_generation": "true"],
        done: true
    )
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(leaf)
    return String(data: data, encoding: .utf8)!
}

func structuredSchema(for family: String) throws -> (GenerationSchema, String, String) {
    if family == "context_trace" {
        let root = DynamicGenerationSchema(
            name: "ExportConfig",
            properties: [
                .init(
                    name: "export_format",
                    description: "Export format. Use jsonl unless the active context explicitly says otherwise.",
                    schema: DynamicGenerationSchema(name: "ExportFormat", anyOf: ["jsonl", "csv"])
                ),
                .init(
                    name: "fields",
                    description: "Required output fields. Include id and value when requested.",
                    schema: DynamicGenerationSchema(
                        arrayOf: DynamicGenerationSchema(type: String.self),
                        minimumElements: 2,
                        maximumElements: 6
                    )
                )
            ]
        )
        return (
            try GenerationSchema(root: root, dependencies: []),
            "answer.json",
            "Generated export configuration from the active context."
        )
    }
    if family == "provenance_bias" {
        let root = DynamicGenerationSchema(
            name: "ClaimAudit",
            properties: [
                .init(
                    name: "action",
                    description: "Audit action for the claim.",
                    schema: DynamicGenerationSchema(name: "AuditAction", anyOf: ["accept", "reject", "repair"])
                ),
                .init(
                    name: "claim",
                    description: "The audited or repaired claim.",
                    schema: DynamicGenerationSchema(type: String.self)
                )
            ]
        )
        return (
            try GenerationSchema(root: root, dependencies: []),
            "audit.json",
            "Generated claim audit from the provided provenance context."
        )
    }
    if family == "mini_workflow" {
        let root = DynamicGenerationSchema(
            name: "WorkflowResult",
            properties: [
                .init(
                    name: "result",
                    description: "The expected result marker from the active invariant.",
                    schema: DynamicGenerationSchema(type: String.self)
                ),
                .init(
                    name: "artifact",
                    description: "The produced artifact filename.",
                    schema: DynamicGenerationSchema(type: String.self)
                )
            ]
        )
        return (
            try GenerationSchema(root: root, dependencies: []),
            "workflow_patch.txt",
            "Generated workflow result from the active context."
        )
    }
    throw NSError(domain: "CoreAILeafBridge", code: 2, userInfo: [
        NSLocalizedDescriptionKey: "No structured schema for family \(family)"
    ])
}

@main
struct CoreAILeafBridge {
    static func main() async {
        do {
            let input = FileHandle.standardInput.readDataToEndOfFile()
            let request = try JSONDecoder().decode(BridgeRequest.self, from: input)
            let model = SystemLanguageModel.default
            let availability = String(describing: model.availability)
            guard model.isAvailable else {
                emit(
                    BridgeResponse(
                        ok: false,
                        content: nil,
                        error: "SystemLanguageModel is unavailable: \(availability)",
                        availability: availability
                    )
                )
                return
            }
            if request.availabilityOnly == true {
                emit(BridgeResponse(ok: true, content: nil, error: nil, availability: availability))
                return
            }

            let session = LanguageModelSession(
                model: model,
                instructions: request.instructions
            )
            let options = GenerationOptions(
                sampling: .greedy,
                temperature: request.temperature,
                maximumResponseTokens: request.maxTokens ?? 768
            )
            if let family = request.taskFamily, let taskId = request.taskId {
                let (schema, artifact, claim) = try structuredSchema(for: family)
                let response = try await session.respond(
                    to: request.prompt,
                    schema: schema,
                    options: options
                )
                let leafJson = try encodeLeaf(
                    taskId: taskId,
                    answerJson: response.content.jsonString,
                    artifact: artifact,
                    claim: claim
                )
                emit(
                    BridgeResponse(
                        ok: true,
                        content: leafJson,
                        error: nil,
                        availability: availability
                    )
                )
                return
            }
            let response = try await session.respond(to: request.prompt, options: options)
            emit(
                BridgeResponse(
                    ok: true,
                    content: response.content,
                    error: nil,
                    availability: availability
                )
            )
        } catch {
            emit(
                BridgeResponse(
                    ok: false,
                    content: nil,
                    error: String(describing: error),
                    availability: "unknown"
                )
            )
        }
    }
}
