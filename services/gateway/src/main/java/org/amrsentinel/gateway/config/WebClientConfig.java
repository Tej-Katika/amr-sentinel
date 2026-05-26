package org.amrsentinel.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Value("${services.ingestion}")
    private String ingestionUrl;

    @Value("${services.intelligence}")
    private String intelligenceUrl;

    @Value("${services.agentic}")
    private String agenticUrl;

    @Bean(name = "ingestionClient")
    public WebClient ingestionClient() {
        return WebClient.builder().baseUrl(ingestionUrl).build();
    }

    @Bean(name = "intelligenceClient")
    public WebClient intelligenceClient() {
        return WebClient.builder().baseUrl(intelligenceUrl).build();
    }

    @Bean(name = "agenticClient")
    public WebClient agenticClient() {
        return WebClient.builder().baseUrl(agenticUrl).build();
    }
}
