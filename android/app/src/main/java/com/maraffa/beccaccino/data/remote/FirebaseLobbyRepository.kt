package com.maraffa.beccaccino.data.remote

import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.database.ValueEventListener
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameRoom
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.RoomStatus
import com.maraffa.beccaccino.data.repository.LobbyRepository
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.random.Random

@Singleton
class FirebaseLobbyRepository @Inject constructor(
    private val database: FirebaseDatabase
) : LobbyRepository {

    private val roomsRef get() = database.getReference("rooms")
    private val gameStatesRef get() = database.getReference("gameStates")

    override suspend fun createRoom(hostUid: String, hostDisplayName: String): Result<GameRoom> =
        runCatching {
            val roomRef = roomsRef.push()
            val roomId = roomRef.key ?: error("Firebase push returned null key")
            val roomCode = generateRoomCode()

            val room = GameRoom(
                roomId = roomId,
                roomCode = roomCode,
                hostUid = hostUid,
                status = RoomStatus.OPEN,
                playerUids = listOf(hostUid),
                createdAt = System.currentTimeMillis()
            )

            // Initial game state
            val initialGameState = mapOf(
                "roomId" to roomId,
                "phase" to GamePhase.WAITING_FOR_PLAYERS.name,
                "players" to mapOf(
                    hostUid to mapOf(
                        "uid" to hostUid,
                        "displayName" to hostDisplayName,
                        "seatIndex" to 0,
                        "isConnected" to true,
                        "isReady" to false
                    )
                ),
                "currentTrick" to mapOf("index" to 0, "plays" to emptyList<Any>(), "ledSuit" to "", "winnerUid" to "", "isComplete" to false),
                "completedTricks" to emptyMap<String, Any>(),
                "declarations" to emptyMap<String, Any>(),
                "trumpSuit" to "",
                "currentTurnUid" to "",
                "dealerSeatIndex" to 0,
                "handNumber" to 0,
                "cumulativeScore" to mapOf("0" to 0, "1" to 0),
                "marafonaTeam" to -1,
                "lastUpdatedAt" to ServerValue.TIMESTAMP
            )

            // Write room and initial game state atomically
            database.reference.updateChildren(mapOf(
                "rooms/$roomId" to mapOf(
                    "roomId" to roomId,
                    "roomCode" to roomCode,
                    "hostUid" to hostUid,
                    "status" to RoomStatus.OPEN.name,
                    "playerUids" to listOf(hostUid),
                    "createdAt" to ServerValue.TIMESTAMP
                ),
                "gameStates/$roomId" to initialGameState
            )).await()

            room
        }

    override suspend fun joinRoom(roomCode: String, uid: String, displayName: String): Result<String> =
        runCatching {
            // Find room by code
            val roomSnap = withContext(Dispatchers.IO) {
                roomsRef.orderByChild("roomCode")
                    .equalTo(roomCode.uppercase())
                    .get().await()
            }

            if (!roomSnap.exists() || !roomSnap.hasChildren()) {
                error("Room not found with code: $roomCode")
            }

            val roomData = roomSnap.children.first()
            val roomId = roomData.key ?: error("Invalid room data")
            val status = roomData.child("status").getValue(String::class.java)
            if (status != RoomStatus.OPEN.name) error("Room is not open for joining")

            val currentPlayerUids = roomData.child("playerUids").children
                .mapNotNull { it.getValue(String::class.java) }
            if (currentPlayerUids.size >= 4) error("Room is full")
            if (uid in currentPlayerUids) error("Already in this room")

            val seatIndex = currentPlayerUids.size  // Next available seat (0-indexed)
            val updatedPlayerUids = currentPlayerUids + uid

            database.reference.updateChildren(mapOf(
                "rooms/$roomId/playerUids" to updatedPlayerUids,
                "gameStates/$roomId/players/$uid" to mapOf(
                    "uid" to uid,
                    "displayName" to displayName,
                    "seatIndex" to seatIndex,
                    "isConnected" to true,
                    "isReady" to false
                )
            )).await()

            roomId
        }

    override fun observeRoom(roomId: String): Flow<GameRoom> = callbackFlow {
        val ref = roomsRef.child(roomId)
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val room = snapshot.toGameRoom() ?: return
                trySend(room)
            }
            override fun onCancelled(error: DatabaseError) {
                close(error.toException())
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }.flowOn(Dispatchers.IO)

    override suspend fun startGame(roomId: String): Result<Unit> = runCatching {
        database.reference.updateChildren(mapOf(
            "rooms/$roomId/status" to RoomStatus.IN_PROGRESS.name
        )).await()
    }

    private fun generateRoomCode(): String {
        val chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  // Omit ambiguous chars (0,O,1,I)
        return (1..6).map { chars[Random.nextInt(chars.length)] }.joinToString("")
    }

    private fun DataSnapshot.toGameRoom(): GameRoom? = runCatching {
        val playerUids = child("playerUids").children
            .mapNotNull { it.getValue(String::class.java) }
        GameRoom(
            roomId = child("roomId").getValue(String::class.java) ?: key ?: return null,
            roomCode = child("roomCode").getValue(String::class.java) ?: "",
            hostUid = child("hostUid").getValue(String::class.java) ?: "",
            status = runCatching {
                RoomStatus.valueOf(child("status").getValue(String::class.java) ?: "OPEN")
            }.getOrDefault(RoomStatus.OPEN),
            playerUids = playerUids,
            createdAt = child("createdAt").getValue(Long::class.java) ?: 0L
        )
    }.getOrNull()
}
