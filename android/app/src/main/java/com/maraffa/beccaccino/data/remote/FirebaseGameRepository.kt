package com.maraffa.beccaccino.data.remote

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.database.ValueEventListener
import com.maraffa.beccaccino.data.model.Declaration
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.Trick
import com.maraffa.beccaccino.data.repository.GameRepository
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.Dispatchers
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FirebaseGameRepository @Inject constructor(
    private val database: FirebaseDatabase,
    private val auth: FirebaseAuth
) : GameRepository {

    private fun gameStateRef(roomId: String) =
        database.getReference("gameStates/$roomId")

    private fun handsRef(roomId: String, uid: String) =
        database.getReference("privateHands/$roomId/$uid/cards")

    override fun observeGameState(roomId: String): Flow<GameState> = callbackFlow {
        val ref = gameStateRef(roomId)
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val state = snapshot.toGameState(roomId)
                trySend(state)
            }
            override fun onCancelled(error: DatabaseError) {
                close(error.toException())
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }.flowOn(Dispatchers.IO)

    override fun observeMyHand(roomId: String, uid: String): Flow<List<String>> = callbackFlow {
        val ref = handsRef(roomId, uid)
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val cards = snapshot.children.mapNotNull { it.getValue(String::class.java) }
                trySend(cards)
            }
            override fun onCancelled(error: DatabaseError) {
                close(error.toException())
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }.flowOn(Dispatchers.IO)

    override suspend fun updateGameState(roomId: String, update: Map<String, Any>): Result<Unit> =
        runCatching {
            gameStateRef(roomId).updateChildren(update).await()
        }

    override suspend fun writeHands(roomId: String, hands: Map<String, List<String>>): Result<Unit> =
        runCatching {
            val updates: Map<String, Any> = hands.entries.associate { (uid, cards) ->
                "privateHands/$roomId/$uid/cards" to cards
            }
            database.reference.updateChildren(updates).await()
        }

    override suspend fun setPlayerConnected(roomId: String, uid: String, connected: Boolean) {
        val connRef = gameStateRef(roomId).child("players/$uid/isConnected")
        connRef.setValue(connected)
        if (connected) {
            // Register automatic disconnect handler
            connRef.onDisconnect().setValue(false)
        }
    }

    // ─── Snapshot → GameState mapping ───────────────────────────────────────

    @Suppress("UNCHECKED_CAST")
    private fun DataSnapshot.toGameState(roomId: String): GameState {
        val phaseStr = child("phase").getValue(String::class.java) ?: "WAITING_FOR_PLAYERS"
        val phase = runCatching { GamePhase.valueOf(phaseStr) }.getOrDefault(GamePhase.WAITING_FOR_PLAYERS)

        val playersMap = child("players").children.associate { playerSnap ->
            val uid = playerSnap.key ?: ""
            uid to Player(
                uid = uid,
                displayName = playerSnap.child("displayName").getValue(String::class.java) ?: "",
                seatIndex = playerSnap.child("seatIndex").getValue(Long::class.java)?.toInt() ?: -1,
                isConnected = playerSnap.child("isConnected").getValue(Boolean::class.java) ?: false,
                isReady = playerSnap.child("isReady").getValue(Boolean::class.java) ?: false
            )
        }

        val currentTrickSnap = child("currentTrick")
        val currentTrick = if (currentTrickSnap.exists()) {
            Trick.fromMap(currentTrickSnap.toMap())
        } else {
            Trick()
        }

        val completedTricksMap = child("completedTricks").children.associate { trickSnap ->
            val key = trickSnap.key ?: "0"
            key to Trick.fromMap(trickSnap.toMap())
        }

        val declarationsList = child("declarations").children.mapNotNull { decSnap ->
            Declaration.fromMap(decSnap.toMap())
        }

        val score0 = child("cumulativeScore/0").getValue(Double::class.java)?.toFloat() ?: 0f
        val score1 = child("cumulativeScore/1").getValue(Double::class.java)?.toFloat() ?: 0f

        return GameState(
            roomId = roomId,
            phase = phase,
            players = playersMap,
            currentTrick = currentTrick,
            completedTricks = completedTricksMap,
            trumpSuit = child("trumpSuit").getValue(String::class.java) ?: "",
            currentTurnUid = child("currentTurnUid").getValue(String::class.java) ?: "",
            dealerSeatIndex = child("dealerSeatIndex").getValue(Long::class.java)?.toInt() ?: 0,
            handNumber = child("handNumber").getValue(Long::class.java)?.toInt() ?: 0,
            cumulativeScore = mapOf("0" to score0, "1" to score1),
            declarations = declarationsList,
            marafonaTeam = child("marafonaTeam").getValue(Long::class.java)?.toInt() ?: -1,
            lastUpdatedAt = child("lastUpdatedAt").getValue(Long::class.java) ?: 0L
        )
    }

    @Suppress("UNCHECKED_CAST")
    private fun DataSnapshot.toMap(): Map<String, Any?> {
        return if (hasChildren()) {
            children.associate { it.key!! to it.toMap() }
        } else {
            mapOf("value" to value)
        }.let { map ->
            // For leaf nodes, return the value directly wrapped
            if (!hasChildren() && value != null) {
                // Return a simple map representing this leaf
                children.associate { it.key!! to it.value }
            } else {
                children.associate { child ->
                    child.key!! to if (child.hasChildren()) child.toMap() else child.value
                }
            }
        }
    }
}
