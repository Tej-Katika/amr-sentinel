package org.amrsentinel.gateway.auth;

public record AuthenticatedUser(String userId, String email, String facilityId, String role) {}
