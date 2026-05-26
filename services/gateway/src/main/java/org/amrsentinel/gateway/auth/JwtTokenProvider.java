package org.amrsentinel.gateway.auth;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

@Component
public class JwtTokenProvider {

    private final SecretKey key;
    private final long expirationMs;

    public JwtTokenProvider(@Value("${jwt.secret}") String secret,
                            @Value("${jwt.expiration}") long expirationMs) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expirationMs = expirationMs;
    }

    public String createToken(String userId, String email, String facilityId, String role) {
        Date now = new Date();
        Date exp = new Date(now.getTime() + expirationMs);

        return Jwts.builder()
            .subject(userId)
            .claims(Map.of(
                "email", email,
                "facility_id", facilityId,
                "role", role
            ))
            .issuedAt(now)
            .expiration(exp)
            .signWith(key)
            .compact();
    }

    public Claims parse(String token) {
        return Jwts.parser()
            .verifyWith(key)
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }

    public boolean isValid(String token) {
        try {
            parse(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
