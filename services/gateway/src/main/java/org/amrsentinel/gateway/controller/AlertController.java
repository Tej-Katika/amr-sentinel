package org.amrsentinel.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import org.amrsentinel.gateway.service.ProxyService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final ProxyService proxyService;

    public AlertController(ProxyService proxyService) {
        this.proxyService = proxyService;
    }

    @GetMapping
    public Mono<JsonNode> list(@RequestParam(defaultValue = "ALL") String severity,
                               @RequestParam(defaultValue = "30") int daysBack) {
        Map<String, String> params = new HashMap<>();
        params.put("severity", severity);
        params.put("days_back", String.valueOf(daysBack));
        return proxyService.intelligenceGet("/alerts", params);
    }
}
